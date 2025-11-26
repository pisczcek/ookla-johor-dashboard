import sys

try:
    import requests
except ImportError:
    raise ImportError(
        "❗ Missing dependency: 'requests'\n"
        "➡ Add this line to requirements.txt:\n"
        "requests"
    )

import zipfile
import os
import pandas as pd
import geopandas as gpd

OOKLA_URL = "https://ookla-open-data.s3.amazonaws.com/parquet/performance/type=fixed/year=2024/quarter=4/2024-10-01_performance_fixed_tiles.parquet"

OUTPUT_DIR = "data"
OUTPUT_FILE = f"{OUTPUT_DIR}/ookla_johor.geojson"

# Example: filter only Johor tiles (lat/lon bounding box)
JOHOR_BOUNDS = {
    "min_lon": 103.0,
    "max_lon": 104.5,
    "min_lat": 1.2,
    "max_lat": 2.7,
}

def download_parquet(url, filename="ookla.parquet"):
    print("📥 Downloading Ookla data…")
    r = requests.get(url)
    if r.status_code != 200:
        raise Exception(f"Failed download: HTTP {r.status_code}")

    with open(filename, "wb") as f:
        f.write(r.content)
    return filename


def filter_johor(parquet_path):
    print("📌 Filtering for Johor…")
    df = gpd.read_parquet(parquet_path)

    df = df[
        (df["tile_lon"] >= JOHOR_BOUNDS["min_lon"]) &
        (df["tile_lon"] <= JOHOR_BOUNDS["max_lon"]) &
        (df["tile_lat"] >= JOHOR_BOUNDS["min_lat"]) &
        (df["tile_lat"] <= JOHOR_BOUNDS["max_lat"])
    ]

    return df


def save_geojson(gdf):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    gdf.to_file(OUTPUT_FILE, driver="GeoJSON")
    print(f"✅ Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    try:
        parquet_file = download_parquet(OOKLA_URL)
        gdf = filter_johor(parquet_file)
        save_geojson(gdf)
        print("🎉 Loader completed successfully!")
    except Exception as e:
        print(f"❌ Loader failed: {e}")
        sys.exit(1)
