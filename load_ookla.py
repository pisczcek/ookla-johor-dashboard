"""load_ookla.py

Downloads the latest Ookla Open Data mobile parquet files from the public S3 bucket,
filters to Johor bounding box and writes out a GeoPackage and a smaller GeoJSON for the app.

Usage:
    python load_ookla.py --output data/ookla_johor.gpkg
"""

import argparse
import s3fs
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape, Point
import json
import os
import re
from tqdm import tqdm

# Public Ookla open data bucket prefix (mobile performance)
ROOT = "s3://ookla-open-data/parquet/performance/mobile/"

# Johor bounding box (approx): minx, miny, maxx, maxy (lon/lat)
JOHOR_BBOX = (103.2, 0.5, 104.9, 2.7)

def find_latest_quarter(fs, root=ROOT):
    objs = fs.ls(root, detail=False)
    pattern = re.compile(r"/([0-9]{4})/Q([1-4])/")
    found = set()
    for p in objs:
        m = pattern.search(p)
        if m:
            found.add((int(m.group(1)), int(m.group(2))))
    if not found:
        raise RuntimeError("No quarter directories found in the Ookla open-data prefix.")
    latest = sorted(found, reverse=True)[0]
    return f"{latest[0]}/Q{latest[1]}/"

def load_latest_mobile_johor(output_path="data/ookla_johor.gpkg", bbox=JOHOR_BBOX, sample=None):
    fs = s3fs.S3FileSystem(anon=True)
    latest = find_latest_quarter(fs)
    latest_prefix = ROOT + latest
    print("Latest prefix:", latest_prefix)
    files = fs.ls(latest_prefix, detail=False)
    parquet_files = [f for f in files if f.endswith('.parquet')]
    if not parquet_files:
        raise RuntimeError("No parquet files found in " + latest_prefix)

    columns_keep = [
        'download_mean', 'upload_mean', 'latency_mean', 'cellular_provider', 'tile'
    ]

    chunks = []
    for p in tqdm(parquet_files, desc='Reading parquet files'):
        try:
            df = pd.read_parquet(p, filesystem=fs, columns=columns_keep)
            chunks.append(df)
        except Exception as e:
            print('Warning: failed to read', p, e)

    if not chunks:
        raise RuntimeError('No parquet data could be read.')

    df = pd.concat(chunks, ignore_index=True)
    print('Total rows loaded:', len(df))

    if 'tile' in df.columns and df['tile'].notnull().any():
        def tile_to_centroid(t):
            try:
                geom = shape(json.loads(t))
                return geom.centroid
            except Exception:
                return None
        df['geometry'] = df['tile'].apply(lambda t: tile_to_centroid(t) if pd.notnull(t) else None)
    else:
        if 'lat' in df.columns and 'lon' in df.columns:
            df['geometry'] = df.apply(lambda r: Point(r['lon'], r['lat']), axis=1)
        else:
            raise RuntimeError('No geometry information (tile or lat/lon) in the dataset.')

    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs='EPSG:4326')

    minx, miny, maxx, maxy = bbox
    gdf = gdf.cx[minx:maxx, miny:maxy]
    print('Rows inside Johor bbox:', len(gdf))

    if sample and len(gdf) > sample:
        gdf = gdf.sample(sample, random_state=1)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    gdf.to_file(output_path, driver='GPKG')
    out_geojson = os.path.join(os.path.dirname(output_path), 'ookla_johor.geojson')
    gdf[['download_mean','upload_mean','latency_mean','cellular_provider','geometry']].to_file(out_geojson, driver='GeoJSON')
    print('Saved:', output_path, 'and', out_geojson)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='data/ookla_johor.gpkg')
    parser.add_argument('--sample', type=int, default=None, help='Optionally sample N rows for smaller output')
    args = parser.parse_args()
    load_latest_mobile_johor(output_path=args.output, sample=args.sample)
